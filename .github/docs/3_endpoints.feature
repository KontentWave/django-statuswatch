Feature: 3. Core Feature: Endpoint Monitoring (CRUD)
  As a logged-in user, I need to be able to create, read, and delete endpoints
  so I can monitor my organization's services.

  Background:
    Given the application is running
    And I am logged in as "tony@stark.com" of "Stark Industries"
    And I am on the "/dashboard" page

  @endpoints @crud @task-3
  Scenario: A logged-in user can add an endpoint to monitor (Create/Read)
    Given my endpoint list is empty
    When I add a new endpoint with URL "https://stark-tower.com" and an interval of "5" minutes
    Then I should see "https://stark-tower.com" in my list of monitored endpoints

  @endpoints @crud @task-3
  Scenario: A logged-in user can delete an endpoint (Delete)
    Given I have an endpoint monitoring "https://stark-tower.com"
    When I click the "Delete" button for "https://stark-tower.com"
    And I confirm the deletion
    Then I should NOT see "https://stark-tower.com" in my list of monitored endpoints

  @endpoints @tenancy @task-3
  Scenario: A user can only see endpoints belonging to their own organization (Read)
    Given the user "steve@avengers.org" from "The Avengers" has an endpoint monitoring "https://avengers-compound.com"
    And I have an endpoint monitoring "https://stark-tower.com"
    When I reload the dashboard
    Then I should see "https://stark-tower.com" in the endpoint list
    And I should NOT see "https://avengers-compound.com" in the endpoint list
