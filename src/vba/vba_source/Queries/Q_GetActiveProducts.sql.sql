SELECT TBL_Products.ProductID, TBL_Products.ProductName, TBL_Products.ProductStatus, TBL_Products.CategoryID
FROM TBL_Products
WHERE (((TBL_Products.ProductStatus)=1) AND ((TBL_Products.Discontinued)=False));
