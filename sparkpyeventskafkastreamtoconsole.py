from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, unbase64, base64, split
from pyspark.sql.types import StructField, StructType, StringType, BooleanType, ArrayType, DateType

# create a StructType for the Kafka stedi-events topic which has the Customer Risk JSON that comes from Redis- before Spark 3.0.0, schema inference is not automatic
kafkaStediEventSchema = StructType (
    [
        StructField("customer", StringType()),
        StructField("score", StringType()),
        StructField("riskDate", StringType()),   
    ]
)

# using the spark application object, read a streaming dataframe from the Kafka topic stedi-events as the source
spark = SparkSession.builder.appName("kafka-stedi-events").getOrCreate()
spark.sparkContext.setLogLevel('WARN')

stediEventsRawStreamingDF = spark \
    .readStream \
    .format('kafka') \
    .option('kafka.bootstrap.servers', 'localhost:9092') \
    .option('subscribe', 'stedi-events') \
    .option('startingOffsets', 'earliest') \
    .load()
                                   
# cast the value column in the streaming dataframe as a STRING 
stediEventsStreamingDF = stediEventsRawStreamingDF.selectExpr("cast(value as string) value")

# parse the JSON from the single column "value" with a json object in it, like this:
# +------------+
# | value      |
# +------------+
# |{"custom"...|
# +------------+
#
# and create separated fields like this:
# +------------+-----+-----------+
# |    customer|score| riskDate  |
# +------------+-----+-----------+
# |"sam@tes"...| -1.4| 2020-09...|
# +------------+-----+-----------+
#
# storing them in a temporary view called CustomerRisk
stediEventsStreamingDF.withColumn('value', from_json('value', kafkaStediEventSchema)) \
    .select(col('value.*')) \
    .createOrReplaceTempView('CustomerRisk')

# execute a sql statement against a temporary view, selecting the customer and the score from the temporary view, creating a dataframe called customerRiskStreamingDF
customerRiskStreamingDF = spark.sql("select customer, score from CustomerRisk")


# sink the customerRiskStreamingDF dataframe to the console in append mode
# 
# It should output like this:
#
# +--------------------+-----
# |customer           |score|
# +--------------------+-----+
# |Spencer.Davis@tes...| 8.0|
# +--------------------+-----
customerRiskStreamingDF.writeStream.outputMode('append').format('console').start().awaitTermination()

# Run the python script by running the command from the terminal:
# /home/workspace/submit-event-kafka-streaming.sh
# Verify the data looks correct 