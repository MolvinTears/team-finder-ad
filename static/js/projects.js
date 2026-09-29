document.addEventListener("DOMContentLoaded", () => {
  const complete = document.getElementById("complete-project-btn");
  complete?.addEventListener("click", async () => {
    if (complete.disabled) return;
    complete.disabled = true;
    try {
      await window.postJSON("/projects/" + complete.dataset.id + "/complete/", {});
      document.querySelector(".project-status-black").textContent = "Закрыт";
      complete.remove();
      window.toast("Проект завершён");
    } catch (error) { window.toast(error.message, {type: "error"}); }
    finally { complete.disabled = false; }
  });
  const button = document.getElementById("participate-btn");
  button?.addEventListener("click", async () => {
    if (button.disabled) return;
    button.disabled = true;
    try {
      const result = await window.postJSON("/projects/" + button.dataset.project + "/toggle-participate/", {});
      const list = document.getElementById("participants-list");
      const id = button.dataset.userId;
      document.getElementById("participant-" + id)?.remove();
      if (result.participant) {
        document.getElementById("no-participants")?.remove();
        const link = document.createElement("a");
        link.href = "/users/" + id + "/";
        link.id = "participant-" + id;
        const item = document.createElement("div");
        item.className = "participant-item";
        const avatar = document.createElement("img");
        avatar.src = button.dataset.userAvatar;
        avatar.alt = "Аватар";
        avatar.className = "participant-avatar";
        const info = document.createElement("div");
        info.className = "participant-info";
        const name = document.createElement("span");
        name.className = "participant-name";
        name.textContent = button.dataset.userName;
        const role = document.createElement("span");
        role.className = "participant-role";
        role.textContent = "Участник";
        info.append(name, role);
        item.append(avatar, info);
        link.append(item);
        list.append(link);
      }
      document.getElementById("participants-count").textContent = result.count;
      button.textContent = result.participant ? "Отказаться от участия" : "Участвовать";
      if (!result.participant && button.dataset.closed === "true") button.remove();
    } catch (error) { window.toast(error.message, {type: "error"}); }
    finally { button.disabled = false; }
  });
});
