# golden: polymorphic rewrite using separate join tables instead of imageable_type/id
defmodule MyApp.Media.Image do
  use Ecto.Schema
  import Ecto.Changeset

  schema "images" do
    field :url, :string
    field :alt_text, :string

    many_to_many :users, MyApp.Accounts.User, join_through: "users_images"
    many_to_many :posts, MyApp.Blog.Post, join_through: "posts_images"
    many_to_many :comments, MyApp.Blog.Comment, join_through: "comments_images"

    timestamps(type: :utc_datetime)
  end

  def changeset(image, attrs) do
    image
    |> cast(attrs, [:url, :alt_text])
    |> validate_required([:url])
  end
end

defmodule MyApp.Repo.Migrations.CreateImagesWithJoinTables do
  use Ecto.Migration

  def change do
    create table(:images) do
      add :url, :string, null: false
      add :alt_text, :string

      timestamps(type: :utc_datetime)
    end

    create table(:users_images, primary_key: false) do
      add :user_id, references(:users, on_delete: :delete_all), null: false
      add :image_id, references(:images, on_delete: :delete_all), null: false
    end

    create unique_index(:users_images, [:user_id, :image_id])

    create table(:posts_images, primary_key: false) do
      add :post_id, references(:posts, on_delete: :delete_all), null: false
      add :image_id, references(:images, on_delete: :delete_all), null: false
    end

    create unique_index(:posts_images, [:post_id, :image_id])

    create table(:comments_images, primary_key: false) do
      add :comment_id, references(:comments, on_delete: :delete_all), null: false
      add :image_id, references(:images, on_delete: :delete_all), null: false
    end

    create unique_index(:comments_images, [:comment_id, :image_id])
  end
end
