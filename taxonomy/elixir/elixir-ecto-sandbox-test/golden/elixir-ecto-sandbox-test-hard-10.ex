# golden: async: true with start_supervised + allow/3 replacing shared mode
defmodule MyApp.NotificationServiceTest do
  use MyApp.DataCase, async: true

  alias MyApp.Accounts
  alias MyApp.Notifications.NotificationService

  setup do
    # start_supervised! ties the GenServer lifetime to the test process,
    # so it dies cleanly when the test exits — no lingering references.
    pid = start_supervised!(NotificationService)

    # Grant the GenServer sandbox access. Because allow/3 is per-process
    # and per-connection, we keep async: true — no shared mode needed.
    Ecto.Adapters.SQL.Sandbox.allow(MyApp.Repo, self(), pid)

    {:ok, pid: pid}
  end

  test "notification service records an event to the DB", %{pid: pid} do
    {:ok, user} = Accounts.create_user(%{email: "subscriber@example.com"})

    :ok = NotificationService.notify(pid, user.id, "welcome")

    assert [%{kind: "welcome"}] = Accounts.notifications_for(user.id)
  end
end
