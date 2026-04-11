defmodule MyApp.Accounts.Recent do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User
  alias MyApp.Blog.Comment

  @doc """
  Returns users who have commented in the last 7 days. Expressed purely
  via Ecto's typed `subquery/1` — no raw SQL, no manual ID round-trip.
  The subquery selects distinct user_ids from recent comments; the outer
  query filters users whose id is in that subquery.
  """
  def recently_active do
    seven_days_ago = DateTime.add(DateTime.utc_now(), -7 * 24 * 60 * 60, :second)

    recent_commenters =
      from(c in Comment,
        where: c.inserted_at > ^seven_days_ago,
        distinct: true,
        select: c.user_id
      )

    from(u in User, where: u.id in subquery(recent_commenters))
    |> Repo.all()
  end
end
