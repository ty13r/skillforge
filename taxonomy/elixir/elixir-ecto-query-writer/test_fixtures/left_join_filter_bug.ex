# fixture: left-join converted to inner-join by filtering in WHERE
defmodule MyApp.Accounts.Summary do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Intended to return every user, with their `approved` comments if any.
  The `where: c.approved == true` clause runs AFTER the left join,
  effectively dropping users with no comments (turning the query into
  an inner join). The approval filter must go inside the `on:` clause.
  """
  def users_with_approved_comments do
    from(u in User,
      left_join: c in assoc(u, :comments),
      where: c.approved == true,
      select: {u.id, u.name, count(c.id)},
      group_by: [u.id, u.name]
    )
    |> Repo.all()
  end
end
