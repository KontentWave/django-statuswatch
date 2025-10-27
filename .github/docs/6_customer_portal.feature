Feature: 6. Stripe Customer Portal
  As a Pro plan user, I need to be able to manage my subscription
  so I can update my payment details or cancel my plan.

  Background:
    Given I am logged in as "tony@stark.com" on the "pro" plan
    And I am on the "/billing" page

  @billing @task-6
  Scenario: A Pro user accesses their billing portal
    Given I see a "Manage Subscription" button
    When I click the "Manage Subscription" button
    Then I should be redirected to an external Stripe Customer Portal page
    And my browser URL should contain "https://billing.stripe.com/p/session/"
