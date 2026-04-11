# Golden: Oban worker test using testing: :manual + perform_job/3 — does not use drain_queue
defmodule MyApp.Mailer.DigestWorkerTest do
  use MyApp.DataCase, async: true
  use Oban.Testing, repo: MyApp.Repo

  alias MyApp.Mailer.DigestWorker
  alias MyApp.Accounts

  test "delivers digests to all opted-in users" do
    {:ok, alice} = Accounts.create_user(%{email: "alice@example.com", digest_opt_in: true})
    {:ok, _bob} = Accounts.create_user(%{email: "bob@example.com", digest_opt_in: false})

    # Use perform_job/3 to execute the worker synchronously in the test process
    # with string-keyed args (Oban's convention). This sees the sandbox data
    # because it runs inside the same process that owns the connection.
    assert :ok = perform_job(DigestWorker, %{"user_id" => alice.id})

    assert_delivered_email_to(alice.email)
  end
end
