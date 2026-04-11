# fixture: Oban test using real queue + drain_queue — cannot see sandbox-inserted jobs
defmodule MyApp.Mailer.DigestWorkerTest do
  use MyApp.DataCase, async: true

  alias MyApp.Mailer.DigestWorker
  alias MyApp.Accounts

  test "delivers digests to all opted-in users" do
    {:ok, alice} = Accounts.create_user(%{email: "alice@example.com", digest_opt_in: true})
    {:ok, _bob} = Accounts.create_user(%{email: "bob@example.com", digest_opt_in: false})

    # BUG: job is inserted inside the sandbox transaction, never commits,
    # so Oban.drain_queue/1 (which runs on a separate process against the real DB)
    # never sees it. The test will always report "0 jobs processed".
    {:ok, _job} = DigestWorker.new(%{"user_id" => alice.id}) |> Oban.insert()

    assert %{success: 1, failure: 0} = Oban.drain_queue(queue: :mailers)

    assert_delivered_email_to(alice.email)
  end
end
