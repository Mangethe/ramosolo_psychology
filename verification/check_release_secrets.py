"""Path policy and redacted source scanning. Never open private artifact paths."""
import argparse
import re
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRS = {'instance', 'node_modules', 'uploads', 'private_uploads', 'backups',
                '.booking-test-postgres', 'pgdata', '.postgres-data', '.venv', '.git', '.aws'}
PRIVATE_FILES = re.compile(
    r'(?:\.db(?:-.+)?|\.sqlite[0-9]?(?:-.+)?|\.(?:log|dump|backup|bak|pem|key|p12|pfx|zip|tar|gz|7z))$'
    r'|^(?:credentials|client_secret[^/]*|service-account[^/]*)\.json$', re.I)
TEXT = {'.py', '.js', '.json', '.jsonc', '.toml', '.yml', '.yaml', '.md', '.html', '.ps1', '.ini', '.txt', '.sql'}
PATTERNS = {
    'private-key marker': rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
    'GitHub token pattern': rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})\b',
    'AWS access key pattern': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'Twilio secret pattern': rb'(?i)(?:TWILIO_API_SECRET|TWILIO_AUTH_TOKEN)\s*=\s*["\']?[a-f0-9]{32}\b',
    'Google credential pattern': rb'\b(?:GOCSPX-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{35}|1//[A-Za-z0-9_-]{30,})\b',
    'Supabase secret pattern': rb'\bsb_secret_[A-Za-z0-9_-]{18,}\b',
    'literal credential in URL': rb'(?i)postgres(?:ql)?(?:\+psycopg)?://[^\s:/@"\'<>]+:[^\s/@$"\'<>]+@[^\s/"\'<>]+',
    'JWT credential pattern': rb'\beyJ[A-Za-z0-9_-]{12,}\.eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{32,}\b',
    'literal environment signing key': rb'(?i)(?:FLASK_SECRET_KEY|AUTH_MFA_KEY|AUTH_VERIFICATION_KEY)\s*=\s*["\']?[A-Za-z0-9_-]{32,}',
}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def private_path(name):
    parts = name.lower().split('/')
    filename = parts[-1]
    return (any(part in PRIVATE_DIRS for part in parts[:-1]) or
            name.lower().startswith('supabase/.temp/') or
            (filename.startswith('.env') and name != '.env.example') or bool(PRIVATE_FILES.search(filename)))


def safe_source(name):
    return not private_path(name) and (name == '.env.example' or PurePosixPath(name).suffix in TEXT)


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
    return kind == 'literal environment signing key' and bool(re.search(
        rb'(?i)(?:synthetic|placeholder|replace)[-_]', value))


def git_paths(*args):
    return [item.decode('utf-8', 'replace') for item in git(*args).split(b'\0') if item]


def private_label(path):
    if path.startswith('.booking-test-postgres/'):
        return '.booking-test-postgres/**'
    if 'node_modules/' in path:
        return 'node_modules/**'
    return path


def inventory_tree(paths):
    hits = set()
    for path in paths:
        local = ROOT / path
        if private_path(path):
            hits.add((private_label(path), 'excluded path'))
        elif (safe_source(path) and local.is_file() and not local.is_symlink()
              and local.stat().st_size <= 512 * 1024 and local.resolve().is_relative_to(ROOT)):
            hits.update((path, kind) for kind in matches(local.read_bytes()))
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
            elif mode == '100644' or mode == '100755':
                if kind == 'blob' and safe_source(path) and int(size) <= 512 * 1024:
                    blobs.setdefault(identity, set()).add(path)
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', action='store_true')
    args = parser.parse_args()
    tracked = git_paths('ls-files', '-z')
    untracked = git_paths('ls-files', '--others', '--exclude-standard', '-z')
    current = inventory_tree(set(tracked + untracked))
    historical, commits, blobs = history() if args.history else (set(), 0, 0)
    for path, kind in sorted(current):
        print(f'working-tree | {kind} | {path}')
    for path, kind in sorted(historical):
        print(f'history | {kind} | {path}')
    print(f'scan counts | current paths {len(set(tracked + untracked))} | commits {commits} | source blobs {blobs}')
    return int(bool(current))


if __name__ == '__main__':
    raise SystemExit(main())
