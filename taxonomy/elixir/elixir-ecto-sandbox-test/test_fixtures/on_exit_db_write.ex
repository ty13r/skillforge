# fixture: Test uses on_exit to do a DB write — ownership error because on_exit runs in a different process
defmodule MyApp.AuditTrailTest do
  use MyApp.DataCase, async: true

  alias MyApp.Accounts
  alias MyApp.AuditTrail

  setup do
    {:ok, user} = Accounts.create_user(%{email: "audit@example.com"})

    # BUG: on_exit runs in a process OTHER than the test process.
    # The test process owns the sandbox connection; the on_exit process does not.
    # This Repo call produces DBConnection.OwnershipError.
    on_exit(fn ->
      AuditTrail.record_event(user.id, "test_exited")
    end)

    {:ok, user: user}
  end

  test "records an event when something happens", %{user: user} do
    AuditTrail.record_event(user.id, "something_happened")

    assert [%{event: "something_happened"}] = AuditTrail.for_user(user.id)
  end
end
