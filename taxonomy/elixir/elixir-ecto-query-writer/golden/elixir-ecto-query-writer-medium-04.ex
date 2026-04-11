defmodule MyApp.Accounts.Summary do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Returns every user along with the count of their approved comments.
  The `approved` filter lives inside the join's `on:` clause, preserving
  the outer-join semantics — users with zero approved comments still
  appear in the result set with a count of 0.
  """
  def users_with_approved_comments do
    from(u in User,
      left_join: c in assoc(u, :comments),
      on: c.approved == true,
      select: {u.id, u.name, count(c.id)},
      group_by: [u.id, u.name]
    )
    |> Repo.all()
  end
end
