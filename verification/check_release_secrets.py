"""Path policy and redacted source scanning. Never open private artifact paths."""
import argparse
import re
import stat
import subprocess
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRS = {'instance', 'node_modules', 'uploads', 'private_uploads', 'backups',
                '.booking-test-postgres', 'pgdata', '.postgres-data', '.venv', 'venv', '.git', '.aws',
                '.pytest_cache', '__pycache__'}
PRIVATE_FILES = re.compile(
    r'(?:\.db(?:-.+)?|\.sqlite[0-9]?(?:-.+)?|\.(?:log|dump|backup|bak|pem|key|p12|pfx|zip|tar|gz|7z|whl|tgz|pyc))$'
    r'|^(?:credentials|client_secret[^/]*|service[-_]account[^/]*)\.json$', re.I)
TEXT = {'.py', '.js', '.mjs', '.css', '.map', '.patch', '.json', '.jsonc', '.toml', '.yml',
        '.yaml', '.md', '.html', '.ps1', '.ini', '.txt', '.sql', '.conf', '.sh', '.cfg',
        '.service', '.bat', '.cmd', '.xml', '.ts', '.jsx', '.tsx', '.diff'}
CONFIG_NAMES = {'caddyfile', 'dockerfile', 'makefile', 'procfile'}
PRIVATE_CONFIGS = {'.flaskenv', '.npmrc', '.pypirc', '.pgpass', 'pgpass.conf'}
MAX_SOURCE_BYTES = 2 * 1024 * 1024
PATTERNS = {
    'private-key marker': rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
    'GitHub token pattern': rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})\b',
    'AWS access key pattern': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'Twilio secret pattern': rb'(?i)(?:TWILIO_API_SECRET|TWILIO_AUTH_TOKEN)\s*=\s*["\']?[a-f0-9]{32}\b',
    'Google credential pattern': rb'\b(?:GOCSPX-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{35}|1//[A-Za-z0-9_-]{30,})\b',
    'Supabase secret pattern': rb'\bsb_secret_[A-Za-z0-9_-]{18,}\b',
    'literal credential in URL': rb'(?i)postgres(?:ql)?(?:\+psycopg)?://[^\s:/@"\'<>]+:[^\s/@$"\'<>]+@[^\s/"\'<>]+',
    'JWT credential pattern': rb'\beyJ[A-Za-z0-9_-]{12,}\.eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{32,}\b',
    'literal environment signing key': rb'(?i)(?:FLASK_SECRET_KEY|AUTH_MFA_KEY|AUTH_VERIFICATION_KEY)["\']?\s*[:=]\s*["\']?[A-Za-z0-9_-]{32,}',
    'literal provider or SMS credential': rb'(?im)^\s*(?:export +)?["\']?(?:AUTH_OIDC_CLIENT_SECRET|GMAIL_OAUTH_CLIENT_SECRET|GMAIL_OAUTH_REFRESH_TOKEN|GMAIL_APP_PASSWORD|TWILIO_API_SECRET|SMS_KEY|SMS_LIMIT_KEY)["\']?\s*[:=]\s*["\']?([A-Za-z0-9_./+=-]{12,}|[a-z]{4}(?: [a-z]{4}){3})(?=["\'\s,]|$)',
}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def private_path(name):
    parts = name.lower().replace('\\', '/').split('/')
    filename = parts[-1]
    return (any(part in PRIVATE_DIRS or part in PRIVATE_CONFIGS for part in parts) or 'supabase/.temp/' in name.lower() or
            any(part.startswith('.env') for part in parts[:-1]) or
            (filename.startswith('.env') and filename != '.env.example') or bool(PRIVATE_FILES.search(filename)))


def safe_source(name):
    path = PurePosixPath(name)
    return not private_path(name) and (
        path.name == '.env.example' or path.name.lower() in CONFIG_NAMES or path.suffix.lower() in TEXT)


def matches(data):
    for kind, pattern in PATTERNS.items():
        candidates = re.finditer(pattern, data)
        if any(not is_placeholder(kind, match[0]) for match in candidates):
            yield kind


def is_placeholder(kind, value):
    if kind == 'literal credential in URL':
        authority = value.split(b'://', 1)[1].lower()
        return bool(re.fullmatch(rb'(?:user|username):password@host(?::\d+)?', authority) or re.search(
            rb'@(?:localhost|127\.0\.0\.1|[a-z0-9.-]+\.(?:test|invalid))(?::\d+)?$', authority))
    return kind in {'literal environment signing key', 'literal provider or SMS credential'} and bool(re.search(
        rb'(?i)[:=]\s*["\']?(?:synthetic|placeholder|replace|example)[-_]', value))


def git_paths(*args):
    return [item.decode('utf-8', 'replace') for item in git(*args).split(b'\0') if item]


def private_label(path):
    if path.startswith('.booking-test-postgres/'):
        return '.booking-test-postgres/**'
    if 'node_modules/' in path:
        return 'node_modules/**'
    return path


def inventory_tree(paths, root=ROOT):
    hits = set()
    for path in paths:
        local = root / path
        if private_path(path):
            hits.add((private_label(path), 'excluded path'))
        elif safe_source(path) and local.is_file():
            if local.is_symlink() or local.resolve() != local:
                hits.add((path, 'linked source was skipped'))
            elif local.stat().st_size > MAX_SOURCE_BYTES:
                hits.add((path, 'oversized source was skipped'))
            else:
                hits.update((path, kind) for kind in matches(local.read_bytes()))
    return hits


def artifact_inventory(artifact):
    if artifact.is_symlink() or private_path(artifact.as_posix()) and artifact.suffix.lower() != '.zip':
        raise ValueError('Artifact must be a release directory or ZIP.')
    if artifact.is_dir():
        hits = set()
        for folder, directories, files in artifact.walk():
            for name in directories[:]:
                path = (folder / name).relative_to(artifact).as_posix()
                if private_path(path) or (folder / name).is_symlink():
                    directories.remove(name)
                    hits.add((private_label(path), 'excluded directory'))
            hits.update(inventory_tree(((folder / name).relative_to(artifact).as_posix()
                                        for name in files), artifact))
        return hits
    if artifact.suffix.lower() != '.zip':
        raise ValueError('Artifact must be a release directory or ZIP.')
    hits = set()
    with ZipFile(artifact) as archive:
        for member in archive.infolist():
            path = member.filename.replace('\\', '/')
            parts = path.rstrip('/').split('/')
            if (private_path(path.rstrip('/')) or
                    any(not part or part != part.rstrip(' .') or ':' in part for part in parts)
                    or stat.S_ISLNK(member.external_attr >> 16)):
                hits.add((private_label(path), 'excluded path'))
            elif not member.is_dir() and safe_source(path):
                if member.file_size > MAX_SOURCE_BYTES or member.flag_bits & 1:
                    hits.add((path, 'source was skipped'))
                else:
                    hits.update((path, kind) for kind in matches(archive.read(member)))
    return hits


def history():
    heads = git('rev-list', '--all').decode().splitlines()
    blobs = {}
    hits = set()
    for commit in heads:
        for entry in git_paths('ls-tree', '-r', '-l', '-z', commit):
            metadata, path = entry.split('\t', 1)
            mode, kind, identity, size = metadata.split()
            if private_path(path):
                hits.add((private_label(path), 'historically tracked excluded path'))
            elif safe_source(path):
                if mode in ('100644', '100755') and kind == 'blob' and int(size) <= MAX_SOURCE_BYTES:
                    blobs.setdefault(identity, set()).add(path)
                else:
                    hits.add((path, 'historical source was skipped'))
    with subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT, stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as child:
        for identity, paths in blobs.items():
            child.stdin.write((identity + '\n').encode())
            child.stdin.flush()
            size = int(child.stdout.readline().split()[-1])
            data = child.stdout.read(size)
            child.stdout.read(1)
            if len(data) != size:
                raise RuntimeError('Incomplete Git blob read.')
            kinds = tuple(matches(data))
            hits.update((path, kind) for path in paths for kind in kinds)
        child.stdin.close()
    return hits, len(heads), len(blobs)


def staged_sources():
    hits = set()
    for path in git_paths('diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z'):
        if private_path(path):
            hits.add((private_label(path), 'excluded path'))
        elif safe_source(path):
            entry, *_ = git_paths('ls-files', '--stage', '-z', '--', path)
            mode, identity, _ = entry.split('\t', 1)[0].split()
            if mode not in ('100644', '100755') or int(git('cat-file', '-s', identity)) > MAX_SOURCE_BYTES:
                hits.add((path, 'staged source was skipped'))
            else:
                hits.update((path, kind) for kind in matches(git('cat-file', 'blob', identity)))
    return hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--artifact', type=Path, action='append', default=[])
    args = parser.parse_args()
    tracked = git_paths('ls-files', '-z')
    untracked = git_paths('ls-files', '--others', '--exclude-standard', '-z')
    current = inventory_tree(set(tracked + untracked))
    staged = staged_sources()
    historical, commits, blobs = history() if args.history else (set(), 0, 0)
    for path, kind in sorted(current):
        print(f'working-tree | {kind} | {path}')
    for path, kind in sorted(staged):
        print(f'index | {kind} | {path}')
    for path, kind in sorted(historical):
        print(f'history | {kind} | {path}')
    artifact_hits = False
    for index, path in enumerate(args.artifact, start=1):
        supplied = path if path.is_absolute() else ROOT / path
        if supplied.resolve() != supplied or private_path(supplied.parent.as_posix()):
            parser.error('Use a direct path to the release artifact, outside private directories.')
        findings = artifact_inventory(supplied)
        artifact_hits |= bool(findings)
        for member, kind in sorted(findings):
            print(f'artifact {index} | {kind} | {member}')
        print(f'artifact {index} | findings {len(findings)}')
    print(f'scan counts | current paths {len(set(tracked + untracked))} | commits {commits} | source blobs {blobs}')
    return int(bool(current or staged) or artifact_hits)


if __name__ == '__main__':
    raise SystemExit(main())
