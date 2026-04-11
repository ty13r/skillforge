# fixture: Prior Claude turn queried Tidewave (dev DB) and fabricated seed data in the test
# The test file shows the damage — an insert! in setup that has nothing to do with the test's own insert path
defmodule MyApp.SubscriptionsTest do
  use MyApp.DataCase, async: true

  alias MyApp.Accounts
  alias MyApp.Subscriptions
  alias MyApp.Billing.Plan

  setup do
    # BUG: This was added by a prior Claude turn that saw rows in the DEV database via
    # Tidewave MCP and assumed those rows also existed in the test DB. In reality, every
    # test runs in a rolled-back transaction — the test DB is always empty. This insert!
    # collides with other tests' inserts (unique constraint on plan.code) in an async
    # test module and is not what this test needs: this test's own create_subscription/2
    # flow creates the plan. The right fix is to DELETE this block.
    {:ok, _plan} = Repo.insert(%Plan{code: "pro", name: "Pro", price_cents: 999})
    :ok
  end

  test "creates a subscription for a user on the pro plan" do
    {:ok, user} = Accounts.create_user(%{email: "pro@example.com"})

    assert {:ok, subscription} =
             Subscriptions.create_subscription(user, %{plan_code: "pro"})

    assert subscription.plan.code == "pro"
    assert subscription.user_id == user.id
  end
end
