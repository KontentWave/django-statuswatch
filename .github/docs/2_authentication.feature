Feature: 2. User Authentication (Login/Logout)
  As a registered user, I need to be able to log in and log out
  to access my private dashboard and secure my account.

  Background:
    Given the application is running
    And a user from "Stark Industries" exists with email "tony@stark.com" and password "JarvisIsMyP@ssw0rd"

  @auth @task-2
  Scenario: A registered user can log in successfully
    Given I am on the "/login" page
    When I fill in "Email" with "tony@stark.com"
    And I fill in "Password" with "JarvisIsMyP@ssw0rd"
    And I click the "Log In" button
    Then I should be redirected to the "/dashboard" page
    And I should see the heading "Stark Industries Dashboard"

  @auth @task-2
  Scenario: A user cannot log in with invalid credentials
    Given I am on the "/login" page
    When I fill in "Email" with "tony@stark.com"
    And I fill in "Password" with "wrongpassword"
    And I click the "Log In" button
    Then I should remain on the "/login" page
    And I should see an error message "Invalid credentials. Please try again."

  @auth @task-2
  Scenario: A logged-in user can log out
    Given I am logged in as "tony@stark.com"
    When I click the "Log Out" button
    Then I should be redirected to the "/login" page
    And I should see a success message "You have been logged out."