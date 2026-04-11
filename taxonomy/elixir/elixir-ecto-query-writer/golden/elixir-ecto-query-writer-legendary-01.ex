defmodule MyApp.Blog.TopCommenters do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User
  alias MyApp.Blog.Comment

  @doc """
  Returns top-N commenters per category using a correlated subquery with
  a window function (row_number rank inside each category partition).
  The outer query joins the per-user totals and filters to rank <= N.
  All values are pinned; the named binding `:commenter` flows through.
  """
  def top_n_per_category(n \\ 3) do
    ranked_inner =
      from(c in Comment,
        join: p in assoc(c, :post),
        group_by: [c.user_id, p.category_id],
        select: %{
          user_id: c.user_id,
          category_id: p.category_id,
          total: count(c.id),
          rank:
            row_number()
            |> over(partition_by: p.category_id, order_by: [desc: count(c.id)])
        }
      )

    from(r in subquery(ranked_inner),
      as: :rank_row,
      join: u in User,
      as: :commenter,
      on: u.id == r.user_id,
      where: r.rank <= ^n,
      select: %{
        category_id: r.category_id,
        user_id: u.id,
        name: u.name,
        total_comments: r.total,
        rank: r.rank
      },
      order_by: [asc: r.category_id, asc: r.rank]
    )
    |> Repo.all()
  end
end
