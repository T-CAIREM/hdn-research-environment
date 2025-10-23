document.addEventListener("DOMContentLoaded", function () {
  const addUserForm = document.querySelector("#add-user-form");
  const userList = document.querySelector("#user-list");
  const emailInput = document.querySelector("#user-email");
  const usersListInput = document.querySelector("#users-list");
  const submitButton = addUserForm.querySelector('button[type="submit"]');
  const originalText = submitButton.innerHTML;
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

  $("#id_project_id").change(function() {
    if (users.length > 0) {
      users = [];
      updateUserList();
    }
  });

  addUserForm.addEventListener("submit", function (event) {
    event.preventDefault();
    const email = emailInput.value.trim();

    if (!email.endsWith("@healthdatanexus.ai")) {
      alert("Please enter a valid email ending with @healthdatanexus.ai.");
      return;
    } else if (users.includes(email)) {
      alert("This user is already added.");
      return;
    }

    submitButton.innerHTML = '<i class="fas fa-spinner fa-pulse"></i> Adding...';
    submitButton.disabled = true;

    $.ajax({
      url: validateCollaboratorUrl,
      data: {
        collaborator_email: email,
        project_id: $("#id_project_id").val(),
      },
      success: function (data) {
        if (data.valid) {
          users.push(email);
          updateUserList();
          emailInput.value = "";
          submitButton.innerHTML = originalText;
          submitButton.disabled = false;
        } else {
          alert(data.error || "This user does not have access to the project.");
          submitButton.innerHTML = originalText;
          submitButton.disabled = false;
        }
      },
      error: function () {
        alert("Failed to check user Project access. Please try again.");
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
      }
    });
  });

  const createEnvironmentForm = document.querySelector(".single-submit-form");
  createEnvironmentForm.addEventListener("submit", function () {
    usersListInput.value = JSON.stringify(users);
    console.log(users)
  });

  updateUserList();
});