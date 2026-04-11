# fixture: DataCase that checks out sandbox but does not handle async tag — every test forced to serial
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

  setup _tags do
    :ok = Ecto.Adapters.SQL.Sandbox.checkout(MyApp.Repo)
    # MISSING: `shared: not tags[:async]` pattern — never calls mode/2, so all tests
    # must be serial to avoid cross-process ownership errors when code spawns workers.
    Ecto.Adapters.SQL.Sandbox.mode(MyApp.Repo, {:shared, self()})
    :ok
  end

  def errors_on(changeset) do
    Ecto.Changeset.traverse_errors(changeset, fn {message, opts} ->
      Regex.replace(~r"%{(\w+)}", message, fn _, key ->
        opts |> Keyword.get(String.to_existing_atom(key), key) |> to_string()
      end)
    end)
  end
end
