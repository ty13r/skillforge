# Golden: async_shared_contradiction fix — remove mode(:shared), keep async: true, use allow/3 where needed
defmodule MyApp.ReportGeneratorTest do
  use MyApp.DataCase, async: true

  alias MyApp.Accounts
  alias MyApp.Reports

  setup do
    # No mode(:shared) call — the DataCase already handles sandbox checkout
    # via start_owner!/2 with shared: not tags[:async]. Async tests get
    # exclusive connections; non-async tests get shared. Do not mix them.
    :ok
  end

  test "generates a report" do
    {:ok, _user} = Accounts.create_user(%{email: "r@example.com"})
    assert %{user_count: 1} = Reports.generate_summary()
  end
end
