// Support file for Cypress E2E tests
// This file is loaded before each E2E test

// Add custom commands if needed
Cypress.Commands.add('login', () => {
  // Implement login if needed
});

Cypress.Commands.add('navigateTo', (path: string) => {
  cy.visit(path);
});

// Disable uncaught exceptions to allow testing error handling
Cypress.on('uncaught:exception', (err) => {
  // Return false to prevent Cypress from failing
  // Return true to let Cypress fail
  return false;
});

// Global error handling
beforeEach(() => {
  // Clear any local storage or session storage
  cy.clearAllLocalStorage();
  cy.clearAllSessionStorage();
});
