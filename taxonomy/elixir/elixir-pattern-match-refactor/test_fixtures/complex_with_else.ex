# fixture: A `with` expression that has flattened all its error clauses into one complex
# else block — the "Complex else clauses in with" official anti-pattern.
defmodule MyApp.Checkout do
  alias MyApp.{Cart, Inventory, Payments, Repo}

  def checkout(cart_id, payment_params) do
    with {:ok, cart} <- Repo.fetch(Cart, cart_id),
         {:ok, items} <- Cart.valid_items(cart),
         {:ok, _} <- Inventory.reserve(items),
         {:ok, charge} <- Payments.charge(cart.total, payment_params),
         {:ok, order} <- Cart.finalize(cart, charge) do
      {:ok, order}
    else
      {:error, :not_found} -> {:error, "Cart not found"}
      {:error, :empty_cart} -> {:error, "Cart is empty"}
      {:error, :out_of_stock} -> {:error, "Some items are out of stock"}
      {:error, :card_declined} -> {:error, "Payment declined"}
      {:error, :insufficient_funds} -> {:error, "Insufficient funds"}
      {:error, :network_error} -> {:error, "Network error — try again"}
      {:error, :duplicate_charge} -> {:error, "Duplicate charge detected"}
      {:error, :finalization_failed} -> {:error, "Could not finalize order"}
      {:error, reason} -> {:error, "Unknown error: #{inspect(reason)}"}
      nil -> {:error, "Unknown"}
      :error -> {:error, "Unknown"}
      _other -> {:error, "Completely unknown"}
    end
  end
end
