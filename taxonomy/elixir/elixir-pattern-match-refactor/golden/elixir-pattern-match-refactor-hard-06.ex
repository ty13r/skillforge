defmodule MyApp.Checkout do
  alias MyApp.{Cart, Inventory, Payments, Repo}

  def checkout(cart_id, payment_params) do
    with {:ok, cart} <- fetch_cart(cart_id),
         {:ok, items} <- validate_items(cart),
         {:ok, _} <- reserve_inventory(items),
         {:ok, charge} <- charge_payment(cart, payment_params),
         {:ok, order} <- finalize_order(cart, charge) do
      {:ok, order}
    end
  end

  defp fetch_cart(cart_id) do
    case Repo.fetch(Cart, cart_id) do
      {:ok, cart} -> {:ok, cart}
      {:error, :not_found} -> {:error, "Cart not found"}
    end
  end

  defp validate_items(cart) do
    case Cart.valid_items(cart) do
      {:ok, items} -> {:ok, items}
      {:error, :empty_cart} -> {:error, "Cart is empty"}
    end
  end

  defp reserve_inventory(items) do
    case Inventory.reserve(items) do
      {:ok, _} = ok -> ok
      {:error, :out_of_stock} -> {:error, "Some items are out of stock"}
    end
  end

  defp charge_payment(cart, payment_params) do
    case Payments.charge(cart.total, payment_params) do
      {:ok, _} = ok -> ok
      {:error, :card_declined} -> {:error, "Payment declined"}
      {:error, :insufficient_funds} -> {:error, "Insufficient funds"}
      {:error, :network_error} -> {:error, "Network error — try again"}
      {:error, :duplicate_charge} -> {:error, "Duplicate charge detected"}
    end
  end

  defp finalize_order(cart, charge) do
    case Cart.finalize(cart, charge) do
      {:ok, order} -> {:ok, order}
      {:error, :finalization_failed} -> {:error, "Could not finalize order"}
    end
  end
end
