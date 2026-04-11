# fixture: Order with line items — should line_items be embedded or associated?
# Correct answer depends on whether line_items need to be queried independently.
# For product analytics, they need independent querying → has_many, not embeds_many.
defmodule MyApp.Sales.Order do
  use Ecto.Schema
  import Ecto.Changeset

  schema "orders" do
    field :customer_name, :string
    field :status, :string
    field :total, :decimal

    # TODO: line items — embed or associate?
    # Note: product analytics team queries line_items directly for revenue by product

    timestamps(type: :utc_datetime)
  end

  def changeset(order, attrs) do
    order
    |> cast(attrs, [:customer_name, :status, :total])
    |> validate_required([:customer_name, :total])
  end
end
