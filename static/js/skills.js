document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("skills-container");
  const addButton = document.getElementById("add-skill-btn");
  if (!container || !addButton) return;
  const project = container.dataset.projectId;
  const wrapper = document.getElementById("skill-input-wrapper");
  const input = document.getElementById("skill-input");
  const suggestions = document.getElementById("skill-suggestions");
  let timer, revision = 0, busy = false;

  function hideInput() {
    revision++;
    clearTimeout(timer);
    wrapper.classList.add("hidden");
    suggestions.classList.add("hidden");
    addButton.classList.remove("hidden");
  }
  addButton.addEventListener("click", () => {
    addButton.classList.add("hidden");
    wrapper.classList.remove("hidden");
    input.value = "";
    suggestions.replaceChildren();
    input.focus();
  });
  input.addEventListener("input", () => {
    clearTimeout(timer);
    const current = ++revision;
    const query = input.value.trim();
    suggestions.replaceChildren();
    suggestions.classList.add("hidden");
    if (!query) return;
    timer = setTimeout(async () => {
      try {
        const response = await fetch("/projects/skills/?q=" + encodeURIComponent(query));
        if (!response.ok) throw new Error("Не удалось загрузить навыки.");
        const skills = await response.json();
        if (current !== revision) return;
        for (const skill of skills) {
          const item = document.createElement("li");
          item.textContent = skill.name;
          item.dataset.id = skill.id;
          item.className = "suggestion-item";
          item.tabIndex = 0;
          suggestions.append(item);
        }
        if (!skills.some(s => s.name.toLowerCase() === query.toLowerCase())) {
          const item = document.createElement("li");
          item.textContent = "Создать «" + query + "»";
          item.dataset.name = query;
          item.className = "create-new";
          item.tabIndex = 0;
          suggestions.append(item);
        }
        suggestions.classList.remove("hidden");
      } catch (error) { window.toast(error.message, {type: "error"}); }
    }, 200);
  });

  function appendChip(skill) {
    if (container.querySelector('[data-id="' + skill.id + '"]')) return;
    const chip = document.createElement("span");
    chip.className = "skill-chip";
    chip.dataset.id = skill.id;
    chip.append(document.createTextNode(skill.name + " "));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-skill-btn";
    remove.textContent = "×";
    remove.setAttribute("aria-label", "Удалить " + skill.name);
    chip.append(remove);
    container.insertBefore(chip, addButton);
    container.querySelector(".skill-empty")?.remove();
  }
  async function add(data) {
    if (busy) return;
    busy = true;
    try {
      const skill = await window.postJSON("/projects/" + project + "/skills/add/", data);
      appendChip(skill);
      hideInput();
    } catch (error) { window.toast(error.message, {type: "error"}); }
    finally { busy = false; }
  }
  function choose(item) {
    if (item) add(item.dataset.id ? {skill_id: item.dataset.id} : {name: item.dataset.name});
  }
  suggestions.addEventListener("click", event => choose(event.target.closest("li")));
  suggestions.addEventListener("keydown", event => {
    if (event.key === "Enter") { event.preventDefault(); choose(event.target.closest("li")); }
    if (event.key === "Escape") hideInput();
  });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (input.value.trim()) add({name: input.value.trim()});
    }
    if (event.key === "Escape") hideInput();
    if (event.key === "ArrowDown") {
      event.preventDefault();
      suggestions.querySelector("li")?.focus();
    }
  });
  container.addEventListener("click", async event => {
    const button = event.target.closest(".remove-skill-btn");
    if (!button || button.disabled) return;
    const chip = button.closest(".skill-chip");
    button.disabled = true;
    try {
      await window.postJSON("/projects/" + project + "/skills/" + chip.dataset.id + "/remove/", {});
      chip.remove();
      if (!container.querySelector(".skill-chip")) {
        const empty = document.createElement("span");
        empty.className = "skill-empty";
        empty.textContent = "Навыки не указаны";
        container.insertBefore(empty, addButton);
      }
    } catch (error) { window.toast(error.message, {type: "error"}); }
    finally { button.disabled = false; }
  });
});
