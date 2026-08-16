Feature: 1. User Registration & Tenant Creation
  As a new visitor, I need to be able to sign up for the service
  so that a new, isolated organization (tenant) is created for me and gated behind email verification.

  Background:
    Given the application is running

  @auth @task-1
  Scenario: Successful registration creates a new organization and requires email verification before login
    Given I am a new visitor on the "/register" page
    When I fill in "Organization Name" with "Stark Industries"
    And I fill in "Email" with "tony@stark.com"
    And I fill in "Password" with "JarvisIsMyP@ssw0rd"
    And I fill in "Confirm Password" with "JarvisIsMyP@ssw0rd"
    And I click the "Sign Up" button
    Then I should see the "Check your inbox" confirmation state
    And a tenant should be created from the organization name "Stark Industries"
    And no authenticated session should be created
    When I complete email verification
    Then I should be redirected to the "/login" page
    And I should see a success message confirming I can now log in
