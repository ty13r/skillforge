# golden: replace Process.sleep with notify+allow+assert_receive synchronization
defmodule MyApp.Inbox.InboxDeliveryTest do
  use MyApp.DataCase, async: true

  alias MyApp.Inbox
  alias MyApp.Inbox.DeliveryWorker
  alias MyApp.Accounts

  test "delivers a message to the inbox" do
    {:ok, user} = Accounts.create_user(%{email: "recipient@example.com"})

    # Start the delivery worker with notify: self() so it can send us
    # a message when delivery is complete. No Process.sleep needed.
    {:ok, worker_pid} =
      DeliveryWorker.deliver_async(user.id, "hello", notify: self())

    # Grant the worker sandbox access so its Repo writes are visible
    # in our test transaction.
    Ecto.Adapters.SQL.Sandbox.allow(MyApp.Repo, self(), worker_pid)

    # Block until the worker signals completion, or fail after 1s.
    assert_receive {:delivered, user_id}, 1_000
    assert user_id == user.id

    assert [%{body: "hello"}] = Inbox.list_messages(user)
  end
end
