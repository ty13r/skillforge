# Golden: Replace Process.sleep with assert_receive to synchronize with the background worker
defmodule MyApp.Inbox.InboxDeliveryTest do
  use MyApp.DataCase, async: true

  alias MyApp.Inbox
  alias MyApp.Inbox.DeliveryWorker
  alias MyApp.Accounts

  test "delivers a message to the inbox" do
    {:ok, user} = Accounts.create_user(%{email: "recipient@example.com"})

    test_pid = self()

    # Start the delivery worker, granting it sandbox access and having it
    # notify us when delivery is complete. No Process.sleep required.
    {:ok, worker_pid} =
      DeliveryWorker.deliver_async(user.id, "hello", notify: test_pid)

    Ecto.Adapters.SQL.Sandbox.allow(MyApp.Repo, self(), worker_pid)

    assert_receive {:delivered, user_id}, 1_000
    assert user_id == user.id

    assert [%{body: "hello"}] = Inbox.list_messages(user)
  end
end
