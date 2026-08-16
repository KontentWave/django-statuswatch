@registration @verification @tenancy
Feature: User Registration & Tenant Creation
  As a prospective customer
  I want to register an organization and verify my email
  So that I can sign in to the correct tenant after verification

  Background:
    Given I am on the public registration page

  @happy @smoke
  Scenario: Successful registration derives the tenant from the organization name
    When I submit the registration form with:
      | organization_name | email                  | password          | password_confirm  |
      | Acme Inc          | owner+acme@example.com | Passw0rd!Passw0rd | Passw0rd!Passw0rd |
    Then the response status is 201
    And I see the "Check your inbox" confirmation state
    And the tenant schema and primary domain are derived from "Acme Inc"
    And an unverified profile is created for "owner+acme@example.com"
    And a verification email is sent

  @negative @validation
  Scenario Outline: Reserved organization slugs are rejected
    When I submit the registration form with:
      | organization_name | email               | password          | password_confirm  |
      | <organization>    | founder@example.com | Passw0rd!Passw0rd | Passw0rd!Passw0rd |
    Then the response status is 400
    And the organization name field reports a reserved-name validation error
    And no tenant is created for "<organization>"

    Examples:
      | organization |
      | www          |
      | api          |
      | admin        |

  @negative @login
  Scenario: Unverified users cannot log in
    Given I registered "Beta Corp" with email "owner+beta@example.com"
    When I attempt to log in with the same credentials before verifying my email
    Then the response status is 403
    And the response contains error.code "email_unverified"
    And I remain unauthenticated

  @email @expiry
  Scenario: Verification tokens expire after 48 hours and cannot be reused
    Given I registered "Delta Co" with email "owner+delta@example.com"
    And the original verification token is older than 48 hours
    When I submit that token for verification
    Then the response status is 400
    And I see that the token has expired
    When I resend verification for "owner+delta@example.com"
    And I submit the new verification token
    Then the response status is 200
    And the email is marked verified
    When I submit that same token again
    Then the response status is 404

  @email @resend
  Scenario: Resend rotates the verification token and invalidates older links
    Given I registered "Gamma LLC" with email "owner+gamma@example.com"
    And I have the first verification token for that account
    When I request "Resend verification email"
    Then a newer verification token is issued for "owner+gamma@example.com"
    And the response tells me to check my inbox without exposing whether the account exists
    When I submit the older verification token
    Then the response status is 404
    When I request a resend for an unknown email address
    Then I receive the same generic resend response

  @redirects
  Scenario: Verification returns the user to login and preserves a safe next path
    Given I attempted to reach "/billing"
    And I registered "Billing Co" with email "owner+billing@example.com"
    When I verify my email with next set to "/billing"
    Then I am taken to the login page
    And I am not automatically authenticated
    When I log in successfully
    Then I am redirected to "/billing"
