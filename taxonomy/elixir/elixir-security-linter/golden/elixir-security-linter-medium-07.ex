# golden: ecto SQL injection fix — replace Ecto.Adapters.SQL.query with parameterized query
defmodule MyApp.Reports do
  import Ecto.Query, warn: false
  alias MyApp.Repo

  def find_by_id(id) do
    {:ok, %{rows: rows}} =
      Ecto.Adapters.SQL.query(Repo, "SELECT * FROM products WHERE id = $1", [id])

    rows
  end

  def product_by_id(id) do
    from(p in MyApp.Catalog.Product, where: p.id == ^id)
    |> Repo.one()
  end
end
