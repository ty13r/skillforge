# Golden: test uses Ecto.Adapters.SQL.Sandbox.allow/3 to grant the spawned Task access to the test's connection
defmodule MyApp.Worker.ReportGeneratorTest do
  use MyApp.DataCase, async: true

  alias MyApp.Accounts
  alias MyApp.Worker.ReportGenerator

  describe "generate/1" do
    test "produces a report that lists all users" do
      {:ok, user} = Accounts.create_user(%{email: "alice@example.com"})

      parent = self()

      # Grant the spawned Task access to the test's sandbox connection.
      # We must pass the child PID, not the supervisor PID.
      {:ok, task_pid} = ReportGenerator.generate_async()
      Ecto.Adapters.SQL.Sandbox.allow(MyApp.Repo, parent, task_pid)

      assert_receive {:report_ready, report}, 1_000
      assert report.user_count == 1
      assert report.user_emails == [user.email]
    end
  end
end
