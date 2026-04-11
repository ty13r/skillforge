# fixture: Product schema without tenant scoping in a multi-tenant app.
# Needs @schema_prefix or query prefix.
defmodule MyApp.Tenant.Product do
  use Ecto.Schema
  import Ecto.Changeset

  schema "products" do
    field :name, :string
    field :sku, :string
    field :price, :decimal

    timestamps(type: :utc_datetime)
  end

  def changeset(product, attrs) do
    product
    |> cast(attrs, [:name, :sku, :price])
    |> validate_required([:name, :sku, :price])
  end
end
