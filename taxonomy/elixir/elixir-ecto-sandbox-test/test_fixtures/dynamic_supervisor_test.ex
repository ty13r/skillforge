# fixture: Test starts a DynamicSupervisor and spawns children that need DB access
# Uses the wrong PID for allow/3 (passes the supervisor PID, not the worker PID)
defmodule MyApp.JobRunnerTest do
  use MyApp.DataCase, async: true

  alias MyApp.JobRunner
  alias MyApp.Accounts

  test "runs a job against a user record" do
    {:ok, user} = Accounts.create_user(%{email: "jobs@example.com"})

    {:ok, supervisor_pid} = DynamicSupervisor.start_link(strategy: :one_for_one)

    # BUG: allow/3 is called on the SUPERVISOR pid, not the child worker pid.
    # The supervisor never performs DB operations; the child does. The child
    # spawned via start_child/2 will fail with a connection ownership error.
    Ecto.Adapters.SQL.Sandbox.allow(MyApp.Repo, self(), supervisor_pid)

    {:ok, _child_pid} =
      DynamicSupervisor.start_child(
        supervisor_pid,
        {JobRunner, user_id: user.id}
      )

    assert_receive {:job_complete, _}, 1_000
  end
end
