PARAMETERS [NewStock] Short, [TargetID] Long;
UPDATE TBL_Products
SET TBL_Products.UnitsInStock = [NewStock]
WHERE (((TBL_Products.ProductID)=[TargetID]));
