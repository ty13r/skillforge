# Golden: Tidewave dev-vs-test trap diagnosis — remove the fabricated seed data and explain
defmodule MyApp.SubscriptionsTest do
  use MyApp.DataCase, async: true

  alias MyApp.Accounts
  alias MyApp.Subscriptions
  alias MyApp.Billing.Plan

  # REMOVED setup block: the previous agent turn inserted %Plan{code: "pro"}
  # here because it saw that row in the DEV database via Tidewave MCP. That
  # is a trap. Every ExUnit test runs in a rolled-back transaction — the test
  # database is empty at the start of every test and reverts at the end.
  # The dev DB is NEVER visible from inside the test transaction.
  #
  # The test below creates its own Plan via the Subscriptions.create_subscription/2
  # flow, which is what we actually want to exercise. Seeding in setup would
  # both mask the real behavior of that function AND cause unique-constraint
  # collisions with other async tests in this module.

  test "creates a subscription for a user on the pro plan" do
    {:ok, user} = Accounts.create_user(%{email: "pro@example.com"})
    {:ok, _plan} = Subscriptions.ensure_plan(%{code: "pro", name: "Pro", price_cents: 999})

    assert {:ok, subscription} =
             Subscriptions.create_subscription(user, %{plan_code: "pro"})

    assert subscription.plan.code == "pro"
    assert subscription.user_id == user.id
  end
end
