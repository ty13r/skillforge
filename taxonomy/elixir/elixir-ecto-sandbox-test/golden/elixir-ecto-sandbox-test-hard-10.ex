# Golden: Fix on_exit DB write by moving to a setup teardown pattern with explicit allowance
defmodule MyApp.AuditTrailTest do
  use MyApp.DataCase, async: true

  alias MyApp.Accounts
  alias MyApp.AuditTrail

  setup do
    {:ok, user} = Accounts.create_user(%{email: "audit@example.com"})
    {:ok, user: user}
  end

  test "records an event when something happens", %{user: user} do
    AuditTrail.record_event(user.id, "something_happened")

    assert [%{event: "something_happened"}] = AuditTrail.for_user(user.id)
  end

  test "audit cleanup is handled by sandbox rollback, not on_exit", %{user: user} do
    # Sandbox rollback automatically reverts every Repo change at the end
    # of the test. We never need on_exit DB writes — the sandbox *is* the cleanup.
    AuditTrail.record_event(user.id, "ephemeral")
    assert length(AuditTrail.for_user(user.id)) == 1
  end
end
