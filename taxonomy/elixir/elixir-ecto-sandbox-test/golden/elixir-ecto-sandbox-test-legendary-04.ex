# Golden: dynamic_supervisor_test fix — allow on the child PID, not the supervisor PID
defmodule MyApp.JobRunnerTest do
  use MyApp.DataCase, async: true

  alias MyApp.JobRunner
  alias MyApp.Accounts

  test "runs a job against a user record" do
    {:ok, user} = Accounts.create_user(%{email: "jobs@example.com"})

    {:ok, supervisor_pid} = DynamicSupervisor.start_link(strategy: :one_for_one)

    {:ok, child_pid} =
      DynamicSupervisor.start_child(
        supervisor_pid,
        {JobRunner, user_id: user.id, caller: self()}
      )

    # Allow the CHILD pid, not the supervisor pid. The supervisor never
    # performs DB operations; the child is the one that needs the sandbox
    # allowance from the test process.
    Ecto.Adapters.SQL.Sandbox.allow(MyApp.Repo, self(), child_pid)

    assert_receive {:job_complete, _}, 1_000
  end
end
