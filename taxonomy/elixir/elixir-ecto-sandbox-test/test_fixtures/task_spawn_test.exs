# fixture: Test that spawns a Task via Task.Supervisor and queries the DB from it — missing allow/3
defmodule MyApp.Worker.ReportGeneratorTest do
  use MyApp.DataCase, async: true

  alias MyApp.Accounts
  alias MyApp.Worker.ReportGenerator

  describe "generate/1" do
    test "produces a report that lists all users" do
      {:ok, user} = Accounts.create_user(%{email: "alice@example.com"})

      # ReportGenerator spawns a Task under ReportSupervisor (an unlinked
      # Task.Supervisor) so the worker is not a child of the test process.
      # It tries to Repo.all(User) but the Task has no DB connection.
      {:ok, task_pid} = ReportGenerator.generate_async()

      assert_receive {:report_ready, report}, 1_000
      assert report.user_count == 1
      assert report.user_emails == [user.email]
    end
  end
end
