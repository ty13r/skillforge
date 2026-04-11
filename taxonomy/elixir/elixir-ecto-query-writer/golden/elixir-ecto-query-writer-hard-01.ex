defmodule MyApp.Accounts.Search do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Filters users by an optional params map using the canonical
  `Enum.reduce/3 + Ecto.Query.dynamic/2` composition. Each present key
  folds a dynamic fragment into the accumulator; absent keys are no-ops.
  The final `where: ^dynamic` is a single where clause with one
  parameterized fragment per filter.
  """
  def search(params) do
    dynamic = build_filter(params)

    from(u in User, where: ^dynamic)
    |> Repo.all()
  end

  defp build_filter(params) do
    Enum.reduce(params, dynamic(true), fn
      {"name", value}, acc when is_binary(value) ->
        dynamic([u], ^acc and ilike(u.name, ^"%#{value}%"))

      {"email", value}, acc when is_binary(value) ->
        dynamic([u], ^acc and u.email == ^value)

      {"min_age", value}, acc when is_integer(value) ->
        dynamic([u], ^acc and u.age >= ^value)

      {"max_age", value}, acc when is_integer(value) ->
        dynamic([u], ^acc and u.age <= ^value)

      {"active", value}, acc when is_boolean(value) ->
        dynamic([u], ^acc and u.active == ^value)

      _, acc ->
        acc
    end)
  end
end
