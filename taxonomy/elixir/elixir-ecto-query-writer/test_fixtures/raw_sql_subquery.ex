# fixture: subquery expressed as raw SQL — should use Ecto subquery/1
defmodule MyApp.Accounts.Recent do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Returns users who have commented in the last 7 days. Currently reaches
  for `Ecto.Adapters.SQL.query/3` — bypassing Ecto's type-safe query DSL
  and losing composability. The idiomatic form uses `subquery/1` with
  `where: u.id in subquery(...)`.
  """
  def recently_active do
    {:ok, %{rows: rows}} =
      Ecto.Adapters.SQL.query(
        Repo,
        """
        SELECT DISTINCT user_id
        FROM comments
        WHERE inserted_at > NOW() - INTERVAL '7 days'
        """,
        []
      )

    ids = List.flatten(rows)

    from(u in User, where: u.id in ^ids)
    |> Repo.all()
  end
end
