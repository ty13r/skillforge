# fixture: shared Comment schema — referenced by preload, aggregate, subquery challenges
defmodule MyApp.Blog.Comment do
  use Ecto.Schema
  import Ecto.Changeset

  schema "comments" do
    field :body, :string
    field :approved, :boolean, default: false
    field :score, :integer, default: 0

    belongs_to :author, MyApp.Accounts.User, foreign_key: :user_id
    belongs_to :post, MyApp.Blog.Post

    timestamps(type: :utc_datetime)
  end

  def changeset(comment, attrs) do
    comment
    |> cast(attrs, [:body, :approved, :score, :user_id, :post_id])
    |> validate_required([:body, :user_id, :post_id])
  end
end
