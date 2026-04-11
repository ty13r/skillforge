# fixture: imperative if/where chaining — non-canonical dynamic query style
defmodule MyApp.Accounts.Search do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Filters users by an optional params map. Currently uses an imperative
  if/where chain which is brittle and does not scale past 3-4 filters.
  The canonical Ecto pattern uses `Enum.reduce/3` over the params map
  with `Ecto.Query.dynamic/2` fragments composed into a single where clause.
  """
  def search(params) do
    query = User

    query =
      if params["name"] do
        where(query, [u], ilike(u.name, ^"%#{params["name"]}%"))
      else
        query
      end

    query =
      if params["email"] do
        where(query, [u], u.email == ^params["email"])
      else
        query
      end

    query =
      if params["min_age"] do
        where(query, [u], u.age >= ^params["min_age"])
      else
        query
      end

    query =
      if params["active"] do
        where(query, [u], u.active == ^params["active"])
      else
        query
      end

    Repo.all(query)
  end
end
