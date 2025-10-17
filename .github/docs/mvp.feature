Feature: 1. User Registration & Tenant Creation
  As a new visitor, I need to be able to sign up for the service
  so that a new, isolated organization (tenant) is created for me.

  Background:
    Given the application is running

  @auth @task-1
  Scenario: Successful registration creates a new, isolated organization
    Given I am a new visitor on the "/register" page
    When I fill in "Organization Name" with "Stark Industries"
    And I fill in "Email" with "tony@stark.com"
    And I fill in "Password" with "JarvisIsMyP@ssw0rd"
    And I click the "Sign Up" button
    Then I should be redirected to the "/login" page
    And I should see a success message "Registration successful. Please log in."