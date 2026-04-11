# fixture: Post/Comment schemas with the foreign-key-on-wrong-side association anti-pattern
# The comment is the child and should have belongs_to :post with FK on the comments table.
defmodule MyApp.Blog.Post do
  use Ecto.Schema
  import Ecto.Changeset

  schema "posts" do
    field :title, :string
    field :body, :string
    # WRONG: belongs_to :comment on Post instead of has_many :comments
    belongs_to :comment, MyApp.Blog.Comment

    timestamps(type: :utc_datetime)
  end

  def changeset(post, attrs) do
    post
    |> cast(attrs, [:title, :body])
    |> validate_required([:title, :body])
  end
end

defmodule MyApp.Blog.Comment do
  use Ecto.Schema
  import Ecto.Changeset

  schema "comments" do
    field :body, :string
    # WRONG: has_many :posts on Comment instead of belongs_to :post
    has_many :posts, MyApp.Blog.Post

    timestamps(type: :utc_datetime)
  end

  def changeset(comment, attrs) do
    comment
    |> cast(attrs, [:body])
    |> validate_required([:body])
  end
end
