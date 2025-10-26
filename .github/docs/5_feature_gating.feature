Feature: 5. Subscription Status & Feature Gating
  As the system, I need to enforce plan limits
  so that only paid users can access Pro features.

  Background:
    Given I am logged in as "tony@stark.com" on the "free" plan
    And I am on the "/dashboard" page

  @billing @gating @task-5
  Scenario: A Free plan user is blocked from adding too many endpoints
    Given I have 3 endpoints currently monitored
    When I try to add a 4th endpoint with URL "https://new-project.com"
    Then I should see an error message "Your 3-endpoint limit reached. Please upgrade to Pro."
    And the endpoint "https://new-project.com" should NOT be added to my list

  @billing @webhooks @task-5
  Scenario: The system activates a Pro plan after a successful payment
    Given the user "tony@stark.com" has just completed a Stripe Checkout
    When the system receives a "checkout.session.completed" webhook from Stripe for "tony@stark.com"
    Then the "Stark Industries" tenant subscription status should be updated to "pro"

  @billing @gating @task-5
  Scenario: A Pro plan user can add unlimited endpoints
    Given I am logged in as "tony@stark.com" on the "pro" plan
    And I have 20 endpoints currently monitored
    When I add a new endpoint with URL "https://project-21.com"
    Then I should see "https://project-21.com" in my list of monitored endpoints
    And I should NOT see any upgrade prompts
