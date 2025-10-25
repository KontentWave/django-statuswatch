Feature: 4. Stripe Subscription Checkout
  As a Free plan user, I need to be able to upgrade to the Pro plan
  so I can monitor unlimited endpoints.

  Background:
    Given I am logged in as "tony@stark.com" on the "free" plan
    And I am on the "/billing" page

  @billing @task-4
  Scenario: A Free user initiates an upgrade to the Pro plan
    Given I see the "Pro Plan" offered at "$9/mo"
    When I click the "Upgrade to Pro" button
    Then I should be redirected to an external Stripe Checkout page
    And my browser URL should contain "https://checkout.stripe.com"
