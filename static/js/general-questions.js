"use strict";

const questions = document.querySelector(".general-question-options");
const reply = document.querySelector(".general-question-reply");

questions.hidden = false;
questions.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-answer]");
  if (!button) return;

  const question = document.createElement("strong");
  question.textContent = button.textContent;
  const answer = document.getElementById(button.dataset.answer);
  reply.replaceChildren(question, answer.content.cloneNode(true));
});
