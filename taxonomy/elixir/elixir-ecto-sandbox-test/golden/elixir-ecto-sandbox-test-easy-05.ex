# Golden: correct mode + checkout ordering — checkout FIRST, then mode(:shared)
defmodule MyApp.DataCase do
  use ExUnit.CaseTemplate

  setup tags do
    :ok = Ecto.Adapters.SQL.Sandbox.checkout(MyApp.Repo)

    unless tags[:async] do
      Ecto.Adapters.SQL.Sandbox.mode(MyApp.Repo, {:shared, self()})
    end

    :ok
  end
end
