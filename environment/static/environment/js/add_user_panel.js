document.addEventListener("DOMContentLoaded", function () {
  const addUserForm = document.querySelector("#add-user-form");
  const userList = document.querySelector("#user-list");
  const emailInput = document.querySelector("#user-email");
  const usersListInput = document.querySelector("#users-list");
  let users = [];

  function updateUserList() {
    userList.innerHTML = "";
    if (users.length === 0) {
      userList.innerHTML = '<li class="list-group-item text-muted">No users added yet.</li>';
    } else {
      users.forEach((user) => {
        const listItem = document.createElement("li");
        listItem.className = "list-group-item d-flex justify-content-between align-items-center";
        listItem.textContent = user;

        const removeButton = document.createElement("button");
        removeButton.className = "btn btn-sm btn-danger";
        removeButton.textContent = "X";
        removeButton.style.padding = "0.2rem 0.5rem";
        removeButton.addEventListener("click", function () {
          users = users.filter((u) => u !== user);
          updateUserList();
        });

        listItem.appendChild(removeButton);
        userList.appendChild(listItem);
      });
    }
    usersListInput.value = JSON.stringify(users);
  }

  addUserForm.addEventListener("submit", function (event) {
    event.preventDefault();
    const email = emailInput.value.trim();

    if (!email.endsWith("@healthdatanexus.ai")) {
      alert("Please enter a valid email ending with @healthdatanexus.ai.");
    } else if (users.includes(email)) {
      alert("This user is already added.");
    } else {
      users.push(email);
      updateUserList();
      emailInput.value = "";
    }
  });

  const createEnvironmentForm = document.querySelector(".single-submit-form");
  createEnvironmentForm.addEventListener("submit", function () {
    usersListInput.value = JSON.stringify(users);
    console.log(users)
  });

  updateUserList();
});