# fixture: Invoice schema with money fields typed as :float — the canonical anti-pattern.
# Named iron law in oliver-kriska/claude-elixir-phoenix.
defmodule MyApp.Billing.Invoice do
  use Ecto.Schema
  import Ecto.Changeset

  schema "invoices" do
    field :customer_id, :integer
    field :subtotal, :float
    field :tax, :float
    field :total, :float
    field :balance, :float
    field :issued_at, :naive_datetime

    timestamps()
  end

  def changeset(invoice, attrs) do
    invoice
    |> cast(attrs, [:customer_id, :subtotal, :tax, :total, :balance, :issued_at])
    |> validate_required([:customer_id, :subtotal, :total])
  end
end
