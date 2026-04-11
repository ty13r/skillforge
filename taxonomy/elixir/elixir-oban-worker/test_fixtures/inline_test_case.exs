# fixture: a test module using :inline mode + assert_enqueued/1
# :inline mode executes jobs synchronously, bypassing the database, so
# assert_enqueued cannot find the job. The correct answer is :manual mode
# with an explicit perform_job/3 or a drain_queue/1 call.
defmodule MyApp.Workers.WelcomeEmailWorkerTest do
  use MyApp.DataCase
  use Oban.Testing, repo: MyApp.Repo

  alias MyApp.Accounts
  alias MyApp.Workers.WelcomeEmailWorker

  setup do
    Application.put_env(:my_app, Oban, testing: :inline)
    :ok
  end

  test "registering a user enqueues a welcome email" do
    {:ok, user} = Accounts.register_user(%{email: "a@b.com"})

    assert_enqueued worker: WelcomeEmailWorker, args: %{user_id: user.id}
  end
end
