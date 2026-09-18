// Run with: node --test environment/tests/test_collaborator_domains.cjs
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");

const readSource = (path) => readFileSync(resolve(__dirname, "..", path), "utf8");
const sources = {
  create: readSource("static/environment/js/add_user_panel.js"),
  manage: readSource("templates/environment/manage_collaborative_environment.html")
    .match(/<script>([\s\S]*?)<\/script>/)[1],
};

function submitCollaborator(form, domain, email) {
  // Only the DOM/jQuery boundary is stubbed; execute the shipping submit handlers.
  const nodes = new Map();
  function node(id) {
    if (!nodes.has(id)) {
      nodes.set(id, {
        dataset: { organizationDomain: domain },
        value: "",
        innerHTML: "",
        style: {},
        listeners: {},
        addEventListener(event, listener) { this.listeners[event] = listener; },
        appendChild() {},
        querySelector: node,
      });
    }
    return nodes.get(id);
  }
  let initialize;
  let requested = false;
  const alerts = [];
  const document = {
    addEventListener(event, listener) { initialize = listener; },
    getElementById: node,
    querySelector: node,
    querySelectorAll: () => [],
    createElement: node,
  };
  const jquery = () => ({
    change() {},
    on() {},
    val: () => "project",
    find: jquery,
    html() {},
    data() {},
    prop() {},
  });
  jquery.ajax = ({ data, success }) => {
    assert.equal(data.collaborator_email, email.trim());
    requested = true;
    success({ valid: true });
  };
  runInNewContext(sources[form], {
    document,
    $: jquery,
    alert: (message) => alerts.push(message),
    validateCollaboratorUrl: "/validate",
    console,
  });
  initialize();
  const formNode = node(form === "create" ? "#add-user-form" : "add-collaborator-form");
  node(form === "create" ? "#user-email" : "collaborator_email").value = email;
  let prevented = false;
  formNode.listeners.submit.call(formNode, {
    preventDefault() { prevented = true; },
  });
  return {
    accepted: form === "create" ? requested : !prevented,
    error: form === "create" ? alerts[0] : node("email-validation-error").style.display,
  };
}

for (const form of ["create", "manage"]) {
  for (const domain of ["physionet.org", "healthdatanexus.ai", "research.example"]) {
    test(`${form}: accepts ${domain}, including mixed case and whitespace`, () => {
      assert.equal(submitCollaborator(form, domain, `colleague@${domain}`).accepted, true);
      assert.equal(submitCollaborator(form, domain, ` colleague@${domain.toUpperCase()} `).accepted, true);
    });
  }

  for (const email of [
    "colleague@healthdatanexus.ai",
    "colleague@evilphysionet.org",
    "colleague@physionet.org.evil",
  ]) {
    test(`${form}: rejects ${email} for PhysioNet`, () => {
      const result = submitCollaborator(form, "physionet.org", email);
      assert.equal(result.accepted, false);
      if (form === "create") assert.match(result.error, /@physionet\.org/);
      else assert.equal(result.error, "block");
    });
  }

  test(`${form}: no inferred domain leaves validation to email input and server`, () => {
    assert.equal(submitCollaborator(form, "", "colleague@research.example").accepted, true);
  });
}
