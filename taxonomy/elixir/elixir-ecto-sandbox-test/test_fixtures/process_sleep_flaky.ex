# fixture: Test uses Process.sleep/1 to coordinate with a background Task — the Iron Law anti-pattern
defmodule MyApp.Inbox.InboxDeliveryTest do
  use MyApp.DataCase, async: true

  alias MyApp.Inbox
  alias MyApp.Inbox.DeliveryWorker
  alias MyApp.Accounts

  test "delivers a message to the inbox" do
    {:ok, user} = Accounts.create_user(%{email: "recipient@example.com"})

    DeliveryWorker.deliver_async(user.id, "hello")

    # BUG: Process.sleep/1 is a code smell — it makes the test both slow (always
    # waits 200ms) and flaky (if the worker takes longer than 200ms the test fails).
    # The correct pattern is assert_receive with a timeout.
    Process.sleep(200)

    assert [%{body: "hello"}] = Inbox.list_messages(user)
  end
end
