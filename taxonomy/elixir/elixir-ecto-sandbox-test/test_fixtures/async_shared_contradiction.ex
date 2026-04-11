# fixture: Test module that declares async: true but uses shared mode — self-contradiction
defmodule MyApp.ReportGeneratorTest do
  use MyApp.DataCase, async: true

  alias MyApp.Accounts
  alias MyApp.Reports

  setup do
    # BUG: we're forcing shared mode AND async: true on the use line above.
    # Shared mode requires async: false because the owner must outlive every
    # allowed worker — async tests run concurrently, so multiple owners would
    # compete for the single shared pool.
    :ok = Ecto.Adapters.SQL.Sandbox.checkout(MyApp.Repo)
    Ecto.Adapters.SQL.Sandbox.mode(MyApp.Repo, {:shared, self()})
    :ok
  end

  test "generates a report" do
    {:ok, _user} = Accounts.create_user(%{email: "r@example.com"})
    assert %{user_count: 1} = Reports.generate_summary()
  end
end
