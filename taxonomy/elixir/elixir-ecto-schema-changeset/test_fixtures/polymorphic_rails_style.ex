# fixture: Rails-style polymorphic association ported directly into Ecto.
# This is the anti-pattern the Ecto docs explicitly warn against.
# "This design breaks database references."
defmodule MyApp.Media.Image do
  use Ecto.Schema
  import Ecto.Changeset

  schema "images" do
    field :url, :string
    field :alt_text, :string
    # WRONG: polymorphic Rails-style — no DB-level FK guarantee
    field :imageable_type, :string
    field :imageable_id, :integer

    timestamps(type: :utc_datetime)
  end

  def changeset(image, attrs) do
    image
    |> cast(attrs, [:url, :alt_text, :imageable_type, :imageable_id])
    |> validate_required([:url, :imageable_type, :imageable_id])
  end
end

defmodule MyApp.Repo.Migrations.CreateImages do
  use Ecto.Migration

  def change do
    create table(:images) do
      add :url, :string, null: false
      add :alt_text, :string
      add :imageable_type, :string, null: false
      add :imageable_id, :integer, null: false

      timestamps(type: :utc_datetime)
    end

    # No FK constraint possible — referential integrity is lost.
    create index(:images, [:imageable_type, :imageable_id])
  end
end
