@e2e @registration @tenancy
Feature: User Registration & Tenant Creation
  As a prospective customer
  I want to register an account and create a tenant (subdomain)
  So that I can access my isolated workspace after verifying my email

  # Assumptions / test env conventions (for step definitions):
  # - BASE_URL points to the public app (e.g., https://app.localhost)
  # - Tenant domains are subdomains of TENANT_ROOT (e.g., https://<slug>.localhost)
  # - Mail UI (Mailpit/MailHog) is available to fetch verification emails
  # - Background jobs (Celery) are configured to deliver emails synchronously in test (or polled)
  # - Verification links are single-use; newest link invalidates older ones

  Background:
    Given I am on the public registration page
    And no tenant exists with subdomain "acme"
    And there is no user registered with email "owner+acme@example.com"

  @happy @smoke
  Scenario: Successful registration creates tenant and sends verification email
    When I submit the registration form with:
      | organization_name | subdomain | full_name     | email                         | password         | accept_terms |
      | Acme Inc          | acme      | Alice Example | owner+acme@example.com        | Passw0rd!Passw0rd| true         |
    Then I see a "Check your email" confirmation screen
    And an email to "owner+acme@example.com" with subject containing "Verify your email" is received
    When I open the latest verification email and follow the verification link
    Then my email is verified
    And I am redirected to "https://acme.localhost/dashboard"
    And I am authenticated on the acme tenant

  @negative
  Scenario: Login blocked until email is verified
    When I submit the registration form with:
      | organization_name | subdomain | full_name     | email                         | password         | accept_terms |
      | Beta Corp         | betacorp  | Bob Example   | owner+beta@example.com        | Passw0rd!Passw0rd| true         |
    And I attempt to log in with email "owner+beta@example.com" and the same password on "https://betacorp.localhost"
    Then I see an error "Please verify your email before logging in"
    And I remain unauthenticated

  @email @resend
  Scenario: Resend verification link invalidates prior links
    Given I have registered "Gamma LLC" with subdomain "gamma" and email "owner+gamma@example.com"
    And I received a verification email for "owner+gamma@example.com"
    When I request "Resend verification email"
    Then a newer verification email for "owner+gamma@example.com" is received
    When I click the older verification link
    Then I see an error "Verification link is invalid or expired"
    When I click the newest verification link
    Then my email is verified
    And I am redirected to "https://gamma.localhost/dashboard"

  @negative @validation
  Scenario Outline: Subdomain validation prevents invalid or reserved names
    When I submit the registration form with:
      | organization_name | subdomain   | full_name | email                       | password         | accept_terms |
      | Bad Org           | <subdomain> | Tester    | owner+bad@example.com       | Passw0rd!Passw0rd| true         |
    Then I see a validation error "<message>"
    And no tenant is created for subdomain "<subdomain>"

    Examples:
      | subdomain | message                                  |
      | www       | Subdomain is reserved                    |
      | api       | Subdomain is reserved                    |
      | admin     | Subdomain is reserved                    |
      | a         | Subdomain is too short                   |
      | -bad-     | Subdomain must start/end with a letter or digit |
      | bad_underscores | Subdomain may contain only letters, digits, and hyphens |
      | way-too-long-subdomain-name-exceeding-the-limit | Subdomain is too long |

  @negative @validation
  Scenario Outline: Organization and user input validation
    When I submit the registration form with:
      | organization_name | subdomain | full_name   | email                | password     | accept_terms |
      | <org_name>        | foobar    | <full_name> | <email>              | <password>   | <accept>     |
    Then I see a validation error "<error>"
    And no tenant is created for subdomain "foobar"

    Examples:
      | org_name | full_name | email                    | password     | accept | error                                   |
      |          | Alice     | alice@example.com        | Passw0rd!!   | true   | Organization name is required           |
      | Foobar   |           | alice@example.com        | Passw0rd!!   | true   | Full name is required                   |
      | Foobar   | Alice     | not-an-email             | Passw0rd!!   | true   | Enter a valid email address             |
      | Foobar   | Alice     | alice@example.com        | short        | true   | Password does not meet requirements     |
      | Foobar   | Alice     | alice@example.com        | password123  | true   | Password does not meet requirements     |
      | Foobar   | Alice     | alice@example.com        | Passw0rd!!   | false  | You must accept the Terms to continue   |

  @uniqueness
  Scenario: Subdomain uniqueness collision is rejected
    Given a tenant already exists with subdomain "acme"
    When I submit the registration form with:
      | organization_name | subdomain | full_name | email                      | password         | accept_terms |
      | Acme Two          | acme      | Alex      | owner+acme2@example.com    | Passw0rd!Passw0rd| true         |
    Then I see a validation error "This subdomain is already taken"
    And my registration is not created

  @uniqueness
  Scenario: Email uniqueness is case-insensitive
    Given a user exists with email "owner@example.com"
    When I submit the registration form with:
      | organization_name | subdomain | full_name | email           | password         | accept_terms |
      | New Org           | neworg    | New User  | OWNER@example.com | Passw0rd!Passw0rd| true         |
    Then I see a validation error "An account with this email already exists"
    And no tenant is created for subdomain "neworg"

  @security @rate-limit
  Scenario: Registration endpoint applies rate limiting per IP
    When I submit invalid registration attempts 10 times from the same IP within 1 minute
    Then the 11th attempt responds with a rate-limit error "Too many requests, please try again later"
    And response status is 429

  @email @negative
  Scenario: Verification link expires after configured TTL
    Given I have registered "Delta Co" with subdomain "delta" and email "owner+delta@example.com"
    And a verification email has been received
    And the verification token has expired
    When I click the verification link
    Then I see an error "Verification link is invalid or expired"
    And I can request a new verification email
    When I request "Resend verification email"
    Then I receive a new verification email
    When I click the new verification link
    Then my email is verified

  @multi-tenant @security
  Scenario: Tenant isolation after verification
    Given I have verified the account for tenant "acme" as "owner+acme@example.com"
    When I navigate to "https://othertenant.localhost/dashboard" while authenticated as "owner+acme@example.com"
    Then I see "Access denied" or I am redirected to login
    And I cannot view resources belonging to "othertenant"

  @progressive-enhancement
  Scenario: Server-side validation works without client-side JS
    Given I have disabled client-side JavaScript
    When I submit the registration form with missing required fields
    Then I see server-rendered validation errors
    And the form preserves the non-sensitive values I entered

  @a11y
  Scenario: Registration form accessibility basics
    When I inspect the registration form
    Then each input has an associated accessible label
    And error messages are announced to screen readers
    And the "Accept Terms" checkbox is keyboard operable and visible with focus

  @i18n
  Scenario: Name normalization keeps user-intended subdomain slug
    When I enter organization name "Žltý Kôň" and desired subdomain "zltykon"
    And I submit the registration form with valid details
    Then the tenant is created at "https://zltykon.localhost"
    And the organization display name is stored as "Žltý Kôň"

  @email @content
  Scenario: Verification email content and metadata
    Given I have registered "Echo Ltd" with subdomain "echo" and email "owner+echo@example.com"
    When the verification email is received
    Then the sender is "no-reply@…"
    And the subject contains "Verify your email"
    And the email body includes a single-use verification link to "https://app.localhost/verify"
    And the link target domain matches the application domain
    And no PII beyond the recipient email is included

  @security
  Scenario: Single-use verification link cannot be reused
    Given I verified my email for tenant "acme" using the verification link
    When I click the same link again
    Then I see "This link has already been used"
    And my session remains authenticated

  @idempotency
  Scenario: Registration is idempotent on network retry before submission completes
    When I submit the registration form for "Foxtrot LLC" and the network times out
    And I retry submission within 30 seconds
    Then at most one user and one tenant are created
    And I receive a single verification email

  @logging @ops
  Scenario: Health and audit events captured during registration
    When I successfully complete registration for "Hotel Inc" subdomain "hotel"
    Then an audit log entry exists for "tenant_created" with subdomain "hotel"
    And an audit log entry exists for "verification_sent" to "owner+hotel@example.com"

  @redirects
  Scenario: Redirect to intended tenant page after verification
    Given I attempted to access "https://acme.localhost/settings" while unverified
    And I was redirected to the "Check your email" screen
    When I verify my email via the link
    Then I am redirected to "https://acme.localhost/settings" (the original intended page)

  @negative
  Scenario Outline: Subdomain auto-sanitization with user confirmation
    When I enter organization name "<org>" and desired subdomain "<input_subdomain>"
    And I submit the registration form
    Then I am prompted "We will use '<sanitized>' as your subdomain" with a confirm option
    When I confirm the sanitized subdomain
    Then the tenant is created at "https://<sanitized>.localhost"

    Examples:
      | org                 | input_subdomain         | sanitized     |
      | My Org!             | my-org!                 | my-org        |
      | Leading Hyphen Inc  | -lead                   | lead          |
      | Trailing Hyphen LLC | tail-                   | tail          |

  @security @csrf
  Scenario: CSRF protection on registration (for non-API form)
    When I submit the registration form without a valid CSRF token
    Then the request is rejected with 403
    And a helpful error message is shown

  @api @jwt
  Scenario: API registration returns minimal safe payload
    When I register via the public API with valid details
    Then the response status is 201
    And the response body does not include access or refresh tokens
    And the response includes "verification_required": true

  @cleanup
  Scenario: Cancelling registration does not create partial tenant
    When I fill the registration form but close the page before submitting
    Then no user and no tenant are created for "cancelme"
