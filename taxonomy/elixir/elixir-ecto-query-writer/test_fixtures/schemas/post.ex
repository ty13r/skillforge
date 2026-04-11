# fixture: shared Post schema — blog-style content with joins to User, Category, Comment
defmodule MyApp.Blog.Post do
  use Ecto.Schema
  import Ecto.Changeset

  schema "posts" do
    field :title, :string
    field :body, :string
    field :slug, :string
    field :published, :boolean, default: false
    field :published_at, :utc_datetime
    field :view_count, :integer, default: 0
    field :score, :float

    belongs_to :author, MyApp.Accounts.User, foreign_key: :user_id
    belongs_to :category, MyApp.Blog.Category
    has_many :comments, MyApp.Blog.Comment

    many_to_many :tags, MyApp.Blog.Tag, join_through: "posts_tags"

    timestamps(type: :utc_datetime)
  end

  def changeset(post, attrs) do
    post
    |> cast(attrs, [:title, :body, :slug, :published, :published_at, :user_id, :category_id])
    |> validate_required([:title, :body, :user_id])
    |> unique_constraint(:slug)
  end
end
