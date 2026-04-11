# fixture: DataCase template with subtle ordering bug — mode(:shared) called before checkout
defmodule MyApp.DataCase do
  use ExUnit.CaseTemplate

  using do
    quote do
      alias MyApp.Repo
      import Ecto
      import Ecto.Changeset
      import Ecto.Query
      import MyApp.DataCase
    end
  end

  setup tags do
    # BUG: mode(:shared) before checkout — the owner isn't established yet,
    # so subsequent checkouts go through a GenServer with no owner to share.
    Ecto.Adapters.SQL.Sandbox.mode(MyApp.Repo, {:shared, self()})
    :ok = Ecto.Adapters.SQL.Sandbox.checkout(MyApp.Repo)

    :ok
  end
end
