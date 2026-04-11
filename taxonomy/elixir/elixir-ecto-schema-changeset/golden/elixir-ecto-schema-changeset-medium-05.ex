# golden: Post/Comment with correct has_many/belongs_to direction
defmodule MyApp.Blog.Post do
  use Ecto.Schema
  import Ecto.Changeset

  schema "posts" do
    field :title, :string
    field :body, :string
    has_many :comments, MyApp.Blog.Comment

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
    belongs_to :post, MyApp.Blog.Post

    timestamps(type: :utc_datetime)
  end

  def changeset(comment, attrs) do
    comment
    |> cast(attrs, [:body, :post_id])
    |> validate_required([:body, :post_id])
    |> foreign_key_constraint(:post_id)
  end
end

defmodule MyApp.Repo.Migrations.CreateCommentsMigration do
  use Ecto.Migration

  def change do
    create table(:comments) do
      add :body, :text, null: false
      add :post_id, references(:posts, on_delete: :delete_all), null: false

      timestamps(type: :utc_datetime)
    end

    create index(:comments, [:post_id])
  end
end
